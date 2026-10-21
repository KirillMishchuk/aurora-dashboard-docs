---
type: pr-report
date: 2026-10-21
status: open
pr: [1383]
issue: [1019]
author: hodanoori
branch: hoda-aurora-network
---

# PR #1383: feat(aurora): add Neutron Networks BFF and read-only Networks page (list & details)

**Author:** hodanoori · **Status:** draft · **Base:** `main` ← `hoda-aurora-network`
**Size:** 18 files, +1346 / −4 · **Created:** 2026-10-12 · [View on GitHub](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1383)

---

## PR Review Report by [review-and-comment-pr](https://github.com/KirillMishchuk/aurora-dashboard-docs/blob/main/ToolDocs/claude-config/aurora-dashboard-config/.claude/skills/review-and-comment-pr/SKILL.md)

### ⚖️ &nbsp; Verdict

Recommendation: **🔴 Request Changes** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **Medium**

The BFF is project-scoped and validates IDs. CI is green on `0a594e9e`, and the security review found nothing. The client closely follows the Routers pattern. Since the earlier review comments, the nav test fix and the merge of `main` have landed.

Two server-side problems block the merge:
- **Shared and external networks are missing from the list.** The `list` procedure forwards the scoped `project_id` to Neutron as a filter, so Neutron returns only networks the project owns.
- **The list is never paginated.** Only the first Neutron page is read.

The PR also overlaps the open #1385 (same feature) and conflicts with Ports #1377. It is still a draft and has no changeset.

Acceptance was graded against the Phase 1 read scope of epic #1019, which the PR links. Most of it is delivered. Still missing: the Status and Shared list filters, and any unit tests.

### 🔧 &nbsp; Required Changes

| #   | Severity    | Category     | Issue                                                                                     | Location                                                                                                     |
| --- | ----------- | ------------ | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| CR1 | 🟠 Major    | Bug          | `list` sends `project_id` to Neutron as a filter, so shared and external networks are hidden | `packages/aurora/src/server/Network/routers/networksRouter.ts:39`                                            |
| CR2 | 🟡 Moderate | Bug          | List reads a single Neutron page: no `limit`/`marker`, `networks_links` ignored            | `packages/aurora/src/server/Network/routers/networksRouter.ts:42`                                            |
| CR3 | 🟡 Moderate | Performance  | Details page fetches the network twice (loader + `useQuery`)                              | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId.tsx:122`                                                                    |
| CR4 | 🟡 Moderate | UI/UX        | 401/403 handled inline instead of via redirect / page-level info `Message`                | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:42`                                                       |
| CR5 | 🟡 Moderate | UI/UX        | Active detail tab kept in `useState` instead of a `tab` search param                      | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:109`                                                |
| CR6 | 🟡 Moderate | Code Quality | Conflicts with open PRs #1385 (same feature) and #1377 (Ports)                            | PR state                                                                                                     |
| CR7 | 🟡 Moderate | UI/UX        | Epic Phase 1 list filters for Status and Shared are not in the UI                         | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/index.tsx:9`                                                                           |
| P1  | —           | Process      | PR is still a draft                                                                       | PR state                                                                                                     |
| P2  | —           | Process      | No changeset, though `packages/aurora/src` changes                                        | `.changeset/`                                                                                                |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**CR1 — `project_id` forwarded to Neutron hides shared and external networks** · Bug · `packages/aurora/src/server/Network/routers/networksRouter.ts:39`
`NetworkQueryParametersSchema` extends `projectScopedInputSchema`, and the `projectScopedProcedure` middleware reads `project_id` without removing it from `input`. The handler takes out only `searchTerm` and `status`:

```ts
const { searchTerm, status, ...openstackFilters } = input
const network = getNetworkService(ctx)

const queryParams = appendQueryParamsFromObject(openstackFilters)
```

`appendQueryParamsFromObject` (`packages/aurora/src/server/helpers/queryParams.ts:33-41`) appends every string key. The request therefore becomes `GET v2.0/networks?project_id=<id>&sort_key=…`. Neutron filters on any top-level attribute, so networks that are shared with the project or external (owned elsewhere) drop out.

The UI has a Shared column and an External field, but it can only ever show the project's own networks. The empty state then reads "There are no networks in this project." (`NetworkListContainer.tsx:92`), and the user can't tell anything is missing. Existing code already guards against this: `floatingIpRouter.ts:182` calls `appendQueryParamsFromObject(omit(input, "project_id"))`. No test covers the query string.

_Fix:_ Drop `project_id` from the filters (`omit(…, "project_id")`, as in `floatingIpRouter.ts:182`) and let Neutron's policy decide visibility under the project-scoped token. Add a router test that asserts the outgoing URL.

**CR2 — List reads only the first Neutron page** · Bug · `packages/aurora/src/server/Network/routers/networksRouter.ts:42`
`list` makes one `GET v2.0/networks` call and parses it with `NetworkListResponseSchema = z.object({ networks: z.array(NetworkSchema) })` (`types/network.ts:32`). The input schema (`types/network.ts:63`) has no `limit` or `marker`, and `networks_links` is never read.

The [Neutron API reference](https://docs.openstack.org/api-ref/network/v2/index.html) (Pagination) says: "To reduce load on the service, list operations will return a maximum number of items at a time." On a deployment that caps page size, only the first page is returned. The BFF-side `searchTerm`/`status` filters (`networksRouter.ts:51`) and the client-side 50-row slicing (`NetworksList.tsx:82-84`) then work on that partial set, with no sign that anything is missing.

Precedent: `routersRouter` doesn't paginate either. @KirylSAP (CR3) and @KirillMishchuk (CR1) raised this in the earlier review comments on this PR, and it is still unaddressed.

_Fix:_ Follow `networks_links` `next` until it runs out, then filter and slice. Add a test with a two-page Neutron response.

**CR3 — Network fetched twice on the details page** · Performance · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId.tsx:122`
The loader awaits `context.trpcClient?.network.networks.getById.query(...)` (`:124`) only to get the page title. The component then calls `trpcReact.network.networks.getById.useQuery(...)` (`:149`) with the same input. The plain client doesn't populate the React Query cache. Every visit therefore makes two identical Neutron requests, and navigation waits for the first one.

Precedent: `$routerId.tsx` does the same, and Copilot raised it on #1355. @KirillMishchuk raised it in the earlier review comment (CR4), and it is still unaddressed.

_Fix:_ In the loader, prefetch through the query client (`queryClient.ensureQueryData` with the tRPC query key) so `useQuery` hits the cache. Alternatively, drop the loader fetch and set the title from the query result.

**CR4 — 401/403 handled inline** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:42`
On the list, a `FORBIDDEN` error is caught and turned into `listError: err.message`. That is rendered as `` <Status status="error" title={t`Failed to Load Networks`} body={listError} /> `` (`:102`): the raw server message, with no retry. On the details page, `UNAUTHORIZED` maps to the inline text "The session has expired. Log in again to continue." (`$networkId.tsx:66`), with no redirect to sign-in.

`copilot-instructions.md` B.6 says: "**Reject** … a 401/403 handled inline instead of via redirect / page-level info `Message`". Precedent: Routers does the same, and the author declined this comment on #1355, so expect pushback. @KirillMishchuk raised it in the earlier review comment (CR3).

_Fix:_ Let 401 go through the session-expiry redirect. Show 403 as a page-level info `Message` with the standard copy instead of the raw `err.message`.

**CR5 — Active tab held in `useState`** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:109`
`const [activeTab, setActiveTab] = useState<NetworkDetailsTab>("overview")` loses the Subnets tab on reload, and the tab can't be linked. The Quick Reject Checklist lists "URL-worthy state held in `useState` instead of search params", and B.9 maps "Active tab → `tab`". Precedent: `RouterDetailsView.tsx:45` does the same.

_Fix:_ Add `tab: z.enum(["overview", "subnets"]).optional()` to the `$networkId` route's `validateSearch`, and drive the tabs from it.

**CR6 — Conflicts with open PRs** · Code Quality · PR state
- **#1385** (open draft) implements the same Networks feature under the same route paths and router key. `git merge-tree` against its head `9ed42505` reports add/add conflicts in `$networkId.tsx`, `NetworkDetailsView.tsx`, `NetworkListContainer.tsx`, `NetworkTableRow.tsx`, `NetworksList.tsx` and `networks/index.tsx`. Only one of the two can land as is.
- **Ports #1377** (head `8394081f`) conflicts in `buildNavSections.test.ts`, the four locale files and `Network/routers/index.ts`.

`main` has not moved since this PR's base, so the PR itself merges cleanly into `main`. The #1386 overlap that earlier comments named is gone, because #1386 is now closed.

_Fix:_ Decide between #1383 and #1385 before more review effort goes in. Agree a merge order with #1377, and keep both `ports` and `networks` in `routers/index.ts`.

**CR7 — Status and Shared filters missing** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/index.tsx:9`
Epic #1019 Phase 1 asks for a "Networks List View with DataGrid, pagination, and filters (Name, Status, Shared)". The list route's search schema has only `search`, `sortBy`, `sortDirection` and `page` (`index.tsx:9-14`), and the toolbar offers search and sort only. The BFF already accepts `status` and `shared` (`types/network.ts:67`, `:72`), but nothing in the UI sends them. @KirillMishchuk raised it in the earlier review comment (I9).

_Fix:_ Add Status and Shared filters to the toolbar and URL state, or note in the PR that they move to a follow-up.

**P1 — PR is a draft** · Process · PR state
The PR is still marked draft, and its description still has a screenshots TODO.
_Fix:_ Mark it ready for review once the items above are addressed.

**P2 — No changeset** · Process · `.changeset/`
The PR changes published code in `packages/aurora/src` (new procedures, routes and a nav entry) but adds no `.changeset/*.md`, so the release workflow won't bump `@cobaltcore-dev/aurora`. Both earlier review comments raised this, and it is still open.
_Fix:_ Run `pnpm changeset` and add a `minor` bump for the new Networks feature.

</details>

### 💡 &nbsp; Improvements

| #   | Severity   | Category      | Issue                                                                          | Location                                                           |
| --- | ---------- | ------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| I1  | 🟢 Low     | Code Quality  | Raw `<button>` for the Subnets-tab retry instead of Juno `Button`              | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:69`       |
| I2  | 🟢 Low     | Code Quality  | `PopupMenu` without `PopupMenuToggle` as trigger                               | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:56`          |
| I3  | 🟢 Low     | UI/UX         | "Log in again" instead of "Sign in"                                            | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId.tsx:66`                           |
| I4  | 🟢 Low     | UI/UX         | All-caps `UP` / `DOWN` strings for admin state                                 | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:46`          |
| I5  | 🟢 Low     | Bug           | `shared` accepted as a sort key, but Neutron doesn't support sorting by it      | `packages/aurora/src/server/Network/types/network.ts:61`           |
| I6  | 🟢 Low     | Docs          | New `networks` service key missing from README / `.env.example` key lists      | `packages/aurora/README.md:183`                                    |
| I7  | 🟢 Low     | UI/UX         | Project overview page has no Networks tile                                     | `packages/aurora/src/client/routes/_auth/projects/$projectId/index.tsx:87` |
| I8  | 🟢 Low     | Code Quality  | Local `withQuery` duplicates the identical copy in `routersRouter.ts`          | `packages/aurora/src/server/Network/routers/networksRouter.ts:22`  |
| I9  | 🟢 Low     | Test coverage | No unit tests for the new router, helpers or components                        | PR files                                                           |
| I10 | ⚪ Trivial | Docs          | Comment says Neutron can't filter by `status`, but it can                      | `packages/aurora/src/server/Network/helpers/networkHelpers.ts:28`  |
| I11 | ⚪ Trivial | Code Quality  | `zod` imported after the lingui imports                                        | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/index.tsx:4`                                 |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**I1 — Raw `<button>`** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:69`
`` action={<button onClick={() => refetch()}>{t`Try Again`}</button>} `` violates the Quick Reject item "Raw HTML element (`<div>`, `<table>`, `<button>`) where a Juno component exists". The sibling `RouterInterfacesTable` uses Juno `Button` for the same retry. @KirylSAP (CR1) and @KirillMishchuk (I1) raised this earlier, and it is still unaddressed.
_Fix:_ Use `` <Button onClick={() => refetch()}>{t`Try Again`}</Button> ``.

**I2 — `PopupMenu` without `PopupMenuToggle`** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:56`
The row menu is `<PopupMenu><PopupMenuOptions>…`. That violates the Quick Reject item "`PopupMenu` without `PopupMenuToggle` as trigger". Juno 9.4.0 still renders its default toggle, so the menu works.

Precedent: `RouterTableRow.tsx` does the same, and the author declined this comment on #1355, so expect pushback. Both earlier review comments raised it.
_Fix:_ `<PopupMenuToggle as="div"><Button icon="moreVert" … /></PopupMenuToggle>` per B.14.

**I3 — "Log in again"** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId.tsx:66`
"The session has expired. Log in again to continue." violates the Quick Reject wording rule (`"Sign In"`/`"Log in"` → use `"Sign in"`). The sibling `$routerId.tsx` has the same text. This string goes away if CR4 is fixed with a redirect.
_Fix:_ "Your session has expired. Sign in again to continue."

**I4 — All-caps strings** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:46`
`` t`UP` `` / `` t`DOWN` `` appear here and at `NetworkDetailsView.tsx:117`. The Quick Reject Checklist bans all-caps strings, and B.19 says "Never all-caps (ever)". The sibling `RouterDetailsView` does the same.
_Fix:_ Use `` t`Up` `` / `` t`Down` ``.

**I5 — `shared` as sort key** · Bug · `packages/aurora/src/server/Network/types/network.ts:61`
`NetworkSortKeySchema = z.enum(["name", "status", "admin_state_up", "shared"])` has the comment "Sort keys supported by Neutron". The [Neutron API reference](https://docs.openstack.org/api-ref/network/v2/index.html) (List networks) limits sort keys to `admin_state_up`, `availability_zone_hints`, `id`, `mtu`, `name`, `status`, `tenant_id` and `project_id`. Its Sorting section adds: "If an API request contains an unknown or unsupported sort key, the server will return a `400` response."

The UI only offers Name and Status, so only direct API callers hit this.
_Fix:_ Remove `shared` from the enum, or replace it with a documented key.

**I6 — Service key not documented** · Docs · `packages/aurora/README.md:183`
The service-key lists at `README.md:183` and `:210` and `apps/dashboard/.env.example:11-12` don't include `networks`. A host with an explicit `enabledServices` whitelist won't see the new nav entry (`buildNavSections.ts:60`) unless it knows the key. `routers` is missing from those lists too, so this follows existing precedent. @KirillMishchuk raised it earlier (I8).
_Fix:_ Add `"networks"` (and `"routers"`) to the README and `.env.example` key lists.

**I7 — No overview tile** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/index.tsx:87`
The project overview page builds tiles for `securitygroups` (`:73`), `floatingips` (`:80`) and `routers` (`:87`). Every other Network nav entry has a tile there, but `networks` doesn't.
_Fix:_ Add an `isEnabled("networks")` tile next to Routers.

**I8 — Duplicate `withQuery`** · Code Quality · `packages/aurora/src/server/Network/routers/networksRouter.ts:22`
This file and `routersRouter.ts` each define the same local `withQuery(baseUrl, params)`.
_Fix:_ Move it to `Network/helpers` and import it in both routers.

**I9 — No unit tests** · Test coverage · PR files
Only `buildNavSections.test.ts` changed. There are no tests for `networksRouter`, `networkHelpers`, the schemas or the four components, although the sibling Routers files have co-located tests. The PR's own "added tests" box is unchecked, and the epic #1019 criterion "Complete testing coverage" is unmet. CR1 and CR2 each need a test of their own.
_Fix:_ Add router tests (query string, pagination, error mapping) and component tests mirroring the Routers suite.

**I10 — Wrong comment on the `status` filter** · Docs · `packages/aurora/src/server/Network/helpers/networkHelpers.ts:28`
The comment `/** Filters Neutron doesn't support directly; applied BFF-side. */` sits above a `status` filter. The Neutron reference lists `status` as a List networks query parameter: "The Networking API v2.0 supports filtering based on all top level attributes of a resource." @KirillMishchuk raised it earlier (I6).
_Fix:_ Correct the comment (for example, the filter runs BFF-side to be case-insensitive), or pass `status` to Neutron.

**I11 — Import order** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/index.tsx:4`
`zod` is imported after `@lingui/core/macro` and `@lingui/react/macro` (`:2-3`). B.13 puts `zod` in group 1, before i18n.
_Fix:_ Move the `zod` import up to line 2.

</details>

---

## Solution Overview

<details>
<summary><strong>What was done</strong></summary>

The PR adds a read-only **Networks** resource under the Network section, covering the Phase 1 read view of epic #1019.

- **Server.** A new `network.networks` tRPC router has three project-scoped queries:
  - `list`: Neutron-side sort, plus BFF-side search and status filter;
  - `getById`;
  - `listSubnets`, for the details page's Subnets tab.

  It comes with Zod schemas for Neutron networks and subnets, and a helper that maps the raw network into a UI shape: `router:external` → `external`, and `subnets[]` → `subnet_count`.
- **Client.** A layout route, a list page and a details page:
  - the list page has URL-backed sort, search and page, with client-side pagination at 50 rows;
  - the details page has Overview and Subnets tabs.

  They are built from four `-components` that mirror the Routers feature.
- **Navigation.** A "Networks" entry is first in the Network sidebar section, gated by `isEnabled("networks")`. The nav test was updated in `f16ad0d2`.
- **Generated files.** `routeTree.gen.ts` and the de/en catalogs are regenerated. Commit `0a594e9e` merged `main` and resolved locale conflicts.

The pages are read-only, with no create, update or delete. The permission keys `network:networks:read`/`list` already existed in the Network permission router, and the PR doesn't call `canUser`, since there are no actions to gate. CI is fully green on `0a594e9e`.

</details>

<details>
<summary><strong>How it is implemented</strong></summary>

**Schemas.** `packages/aurora/src/server/Network/types/network.ts:9` parses Neutron networks leniently. Optional flags get defaults, and the raw `router:external` key is kept for the helper to rename:

```ts
export const NetworkSchema = z.object({
  id: z.string(),
  name: z.string().default(""),
  description: z.string().optional().default(""),
  status: z.string(),
  admin_state_up: z.boolean(),
  shared: z.boolean().optional().default(false),
  // Neutron exposes the external flag as "router:external"
  "router:external": z.boolean().optional().default(false),
  mtu: z.number().nullish(),
```

The list input (`types/network.ts:63`) splits fields between those passed to Neutron and those applied in the BFF. The `projectScopedInputSchema` base also contributes `project_id`, which is the source of CR1.

```ts
export const NetworkQueryParametersSchema = projectScopedInputSchema.extend({
  // Passed through to Neutron
  name: z.string().optional(),
  admin_state_up: z.boolean().optional(),
  shared: z.boolean().optional(),
  sort_key: NetworkSortKeySchema.optional(),
  sort_dir: SortDirSchema.optional(),
  // Applied BFF-side
  searchTerm: z.string().trim().optional(),
  status: z.string().optional(),
})
```

**Mapping.** `packages/aurora/src/server/Network/helpers/networkHelpers.ts:18` derives the UI fields. It still returns the `subnets` ID array alongside `subnet_count`:

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

**Router.** `list` (`packages/aurora/src/server/Network/routers/networksRouter.ts:39`) makes one Neutron call. It then filters by status and searches over `id`, `name` and `description` on the result:

```ts
const { searchTerm, status, ...openstackFilters } = input
const network = getNetworkService(ctx)

const queryParams = appendQueryParamsFromObject(openstackFilters)
const response = await requestOrThrow(
  () => network.get(withQuery(NETWORKS_BASE_URL, queryParams)),
  NetworkErrorHandlers.list
)
```

`getById` (`networksRouter.ts:68`) encodes the ID before putting it in the path. `listSubnets` validates the ID and sends it only as a query parameter, with a fixed `fields` allow-list (`networksRouter.ts:88`):

```ts
// Validates the ID; it is sent as a query param (encoded by URLSearchParams), not as a path segment
validateAndEncodeResourceId(network_id, "Network")

const params = appendQueryParamsFromObject({
  network_id,
  fields: ["id", "name", "cidr", "ip_version", "gateway_ip", "enable_dhcp"],
})
```

All three procedures use `projectScopedProcedure` and the shared `ErrorHandler("Network")` (`networkHelpers.ts:8-12`). The router is mounted as `networks` in `Network/routers/index.ts`.

**List page.** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/index.tsx:9` keeps the list state in the URL:

```ts
const networksSearchFields = {
  search: z.string().optional(),
  sortBy: z.enum(["name", "status"]).optional(),
  sortDirection: z.enum(["asc", "desc"]).optional(),
  page: z.number().int().positive().optional(),
}
```

`NetworksList.tsx` fetches the whole list through a memoized promise read with `use()` and Suspense, and uses `useDeferredValue` to keep the old list visible while the next one loads. Only `FORBIDDEN` is caught into an inline error (`NetworksList.tsx:41`); every other error goes to an ErrorBoundary with "Try Again". Pagination slices the fetched array (`NetworksList.tsx:82`):

```ts
const totalPages = Math.max(1, Math.ceil(networks.length / PAGE_SIZE))
const safePage = Math.min(currentPage, totalPages)
const paginatedNetworks = networks.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)
```

**Details page.** The loader fetches the network only to set the page title (`$networkId.tsx:122`). The component then fetches it again with `useQuery` (`:149`), which is CR3:

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

`NetworkLoadError` maps tRPC codes to HTTP statuses and offers retry only for transient codes. `NetworkDetailsView.tsx:111` lists the Overview fields, with `ClipboardText` for the IDs:

```ts
const overviewItems: DetailItem[] = [
  { label: t`Name`, value: network.name || "—" },
  { label: t`ID`, value: <ClipboardText text={network.id} /> },
  { label: t`Project ID`, value: <ClipboardText text={network.project_id} /> },
  { label: t`Description`, value: network.description || "—" },
  { label: t`Status`, value: network.status },
  { label: t`Admin State`, value: network.admin_state_up ? t`UP` : t`DOWN` },
```

The Subnets tab (`NetworkDetailsView.tsx:47`) runs its own `listSubnets` query and has loading, error, empty and DataGrid states.

**Nav.** `buildNavSections.ts:60` adds the entry ahead of Security Groups:

```ts
...(isEnabled("networks")
  ? [
      {
        service: "networks",
        label: t`Networks`,
        navigate: (nav: NavigateFn) =>
          nav({ to: "/projects/$projectId/network/networks", params: { projectId } }),
        params: { projectId },
      },
    ]
  : []),
```

</details>

<details>
<summary><strong>What it affects (blast radius)</strong></summary>

- **The change is additive.** `network.networks.{list,getById,listSubnets}` extends the `AppRouter` type exported through `./types`. No existing procedure, export or prop changes.
- **No consumers outside the PR.** `git grep` at `0a594e9e` for `networksRouter`, `NetworkListItem`, `NetworkErrorHandlers`, `toNetworkListItem` and `network.networks` finds only the PR's own files. No caller is left stale.
- **New service key `networks`.**
  - It appears for every host that doesn't whitelist services.
  - Hosts with an explicit `enabledServices` list must add the key. The README and `.env.example` key lists don't mention it (I6).
  - The project overview page has no matching tile (I7).
- **Permissions.** `network:networks:read`/`list` already map to `get_network` in `Network/routers/permissionRouter.ts`, and `get_network` is `rule:default_viewer` in `apps/dashboard/src/policies/networking.json`. The PR doesn't add or use `canUser`. Access relies on Neutron's own policy, and its 403 is surfaced in the UI.
- **Consumer documentation.** `packages/aurora/README.md` doesn't describe networks. `packages/aurora/docs` has no networks BFF design doc, though #1385 adds one.
- **Overlap.** The six new client files collide add/add with #1385. `buildNavSections.test.ts`, the locales and `Network/routers/index.ts` collide with Ports #1377 (CR6).

</details>

---

## QA Test Plan

<details>
<summary><strong>Core Path</strong></summary>

1. Open a project whose catalog has Neutron. Under **Network** in the side nav, "Networks" is listed first. Click it; the URL becomes `/projects/<id>/network/networks`.
2. The list shows "Loading Networks...", then a grid with Name/ID, Status, Shared, MTU, Admin State, Subnets and Port Security, plus a row menu.
3. Sort by Status, descending. The URL gets `sortBy=status&sortDirection=desc`, and the order matches Neutron's.
4. Type a search term. After about 500 ms the URL gets `search=…`, and rows match by name, ID or description.
5. With more than 50 networks, pagination appears. Page 2 sets `page=2`.
6. Click a row, or use **Show Details** in the row menu. The details page opens on the Overview tab with Name, ID, Project ID (both copyable), Description, Status, Admin State, Shared, External, MTU, Port Security and Subnets.
7. Open the **Subnets** tab. Rows show Name/ID, CIDR, IP Version, Gateway IP and DHCP.
8. Go back with the browser Back button: the list comes back with its `search`, `sortBy`, `sortDirection` and `page` URL state. The "Networks" breadcrumb navigates without search params, so it opens the default list (name ascending, no search, page 1).

</details>

<details>
<summary><strong>Edge Cases</strong></summary>

- **Shared or external network owned by another project** (CR1). It should appear in the list and doesn't, because `project_id` is sent as a Neutron filter (`networksRouter.ts:39-42`). Compare with `openstack network list`.
- **Deployment with a Neutron page-size cap** (CR2). With more networks than the cap, the extra ones are missing, and search and pagination work on the truncated set (`networksRouter.ts:42-49`, `NetworksList.tsx:82-84`).
- **Details page network tab** (CR3). Open a network with DevTools open: two identical `getById` calls go out (`$networkId.tsx:124`, `:149`).
- **List with a 403** (CR4). An inline "Failed to Load Networks" shows the raw server message, with no retry (`NetworksList.tsx:42-43`, `:102`).
- **Details page with an expired session** (CR4). It shows "The session has expired. Log in again to continue." with no redirect (`$networkId.tsx:66`).
- **Details page 404.** It shows "This network does not exist or has been deleted." with no retry (`$networkId.tsx:62`).
- **Subnets tab, then reload** (CR5). The page comes back on Overview (`NetworkDetailsView.tsx:109`).
- **Subnets query fails.** "Failed to Load Subnets" appears with an unstyled raw `<button>` retry (`NetworkDetailsView.tsx:65-70`).
- **Network without subnets.** It shows "This network has no subnets." (`NetworkDetailsView.tsx:75`).
- **Empty project or no matches.** Each shows its own empty-state text (`NetworkListContainer.tsx:92`).
- **Network with an empty name.** The list, title and breadcrumb fall back to the ID (`NetworkTableRow.tsx:41`, `$networkId.tsx:154`, `:166`).
- **Null `mtu` or `port_security_enabled`.** It shows "–" in the list (`NetworkTableRow.tsx:45`, `:49-50`) and "—" in details (`NetworkDetailsView.tsx:120`, `:124-125`).
- **Invalid URL params** such as `sortBy=foo`, `page=-1` or `page=abc`. Each field falls back on its own (`index.tsx:28-39`). A page beyond the last one resets to 1 (`NetworksList.tsx:97-99`).
- **Project switch.** The list remounts, and the previous project's rows shouldn't flash (`index.tsx:54`).
- **Service gating.** With `enabledServices` set but without `networks`, or with `networks` in `deniedServices`, the nav entry is hidden (`buildNavSections.ts:60`).
- **Direct API call** with `sort_key: "shared"`. Neutron returns 400 (I5).

</details>

---

_Analyzed 2026-10-21 · commit `0a594e9e` · read-only · skill: review-and-comment-pr_

<!-- related:auto — generated from pr/issue properties by tools/update-related.py; do not edit by hand -->
## Related

- plan · 2026-10-12 · [2026-10-12-networks-epic-1019-analysis](../../plans/2026-10-12-networks-epic-1019-analysis.md)
- plan · 2026-10-12 · [2026-10-12-networks-phase-1-read-operations](../../plans/2026-10-12-networks-phase-1-read-operations.md)
- pr-report · 2026-10-17 · [1385-neutron-networks-bff-read-only-networks-page](1385-neutron-networks-bff-read-only-networks-page.md)
- pr-report · 2026-10-17 · [1386-network-and-verify-do-not-merge](1386-network-and-verify-do-not-merge.md)
