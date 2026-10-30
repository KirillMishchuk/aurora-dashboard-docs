---
type: pr-report
date: 2026-10-23
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

A draft that adds a read-only Neutron Networks BFF (`list`, `getById`, subnets) and a Networks list and detail page behind a new `networks` nav key. CI is green, but one bug blocks the merge: `list` forwards `project_id` to Neutron, so shared and external networks the user can see are hidden (CR1). The PR also duplicates the open draft #1385 (CR3), which needs settling before either one merges. Against issue #1019 the PR meets 2 of 8 acceptance criteria, partly meets 4, leaves the permission criterion out of scope and doesn't meet the testing one (no tests for the router, helpers or components). The rest are client-side standards nits.

### 🔧 &nbsp; Required Changes

| #   | Severity    | Category    | Issue                                                                                              | Location                                                                                          |
| --- | ----------- | ----------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| CR1 | 🟠 Major    | Bug         | `networks.list` sends `project_id` to Neutron, so shared and external networks are hidden          | `packages/aurora/src/server/Network/routers/networksRouter.ts:42`                                 |
| CR2 | 🟡 Moderate | Performance | Detail page fetches the same network twice (loader `getById.query` + component `getById.useQuery`) | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId.tsx:124` |
| CR3 | 🟡 Moderate | Conflict    | Duplicates open draft PR #1385 (same Networks BFF + pages); 9 non-generated files conflict         | PR files                                                                                          |
| P1  | —           | Process     | PR is still a draft                                                                                | PR state                                                                                          |
| P2  | —           | Process     | Published package code changed without a `.changeset/*.md`                                         | PR files                                                                                          |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**CR1 — `list` filters by `project_id`, hiding shared and external networks** · Bug · `packages/aurora/src/server/Network/routers/networksRouter.ts:42`
`list` takes out only `searchTerm` and `status` from its input, so `project_id` (required by `projectScopedInputSchema`, `packages/aurora/src/server/trpc.ts:144`) stays in `openstackFilters` and goes to Neutron as a query filter at `packages/aurora/src/server/Network/routers/networksRouter.ts:42`. The [Neutron list-networks reference](https://docs.openstack.org/api-ref/network/v2/#list-networks) says the default policy returns the project's own networks *and* networks shared with it. With `project_id=<id>` in the query, only owned networks come back. Shared tenant networks and external/provider networks owned by another project (usually the ones users attach to) never show up in the list.

The security-group router already solves the same problem: `packages/aurora/src/server/Network/routers/securityGroupRouter.ts:83` fetches own (`project_id`, `shared: false`) and `packages/aurora/src/server/Network/routers/securityGroupRouter.ts:84` fetches shared (`shared: true`), then merges them. The comment at `packages/aurora/src/server/Network/routers/securityGroupRouter.ts:82` explains why simply dropping `project_id` is wrong too: an admin token would then get every project's resources (#1321). No test covers what `list` sends.
_Fix:_ Follow `securityGroupRouter`: fetch owned (`project_id`, `shared=false`) and shared (`shared=true`) networks (plus `router:external=true` if external networks should be listed), merge them by `id`, and add a router test that checks the query parameters.

**CR2 — The network is fetched twice on every detail visit** · Performance · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId.tsx:124`
The `$networkId` loader calls `network.networks.getById.query` at `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId.tsx:124`, but uses the result only for the page title. `RouteComponent` then requests the same input again through `trpcReact.network.networks.getById.useQuery`, so every detail visit makes two identical requests. copilot-instructions A.3 asks for page-critical data to come from the loader.
_Fix:_ Return the network from the loader and read it with `Route.useLoaderData()`, or seed the query cache from the loader (`ensureQueryData`) so `useQuery` doesn't refetch.

**CR3 — Same work as open draft PR #1385** · Conflict · PR files
Open draft #1385 adds the same Neutron Networks BFF and read-only list/detail pages: `networksRouter.ts`, `types/network.ts`, `networkHelpers.ts`, `NetworksList.tsx`, `NetworkDetailsView.tsx`, the routes and the nav entry. Whichever PR merges second runs into real conflicts in 9 non-generated files. #1385 also has a changeset, a design doc (`docs/0017_networks_bff.md`) and tests for the router, helpers, types and components, all of which this PR lacks. Neither the PR body nor the discussion mentions #1385.
_Fix:_ Agree with the author of #1385 which PR goes forward, and close the other or reduce it to whatever it adds on top.

**P1 — PR is still a draft** · Process · PR state
The PR is marked as a draft, so the author doesn't consider it ready to merge yet.
_Fix:_ Mark it ready for review once the Required Changes are addressed.

**P2 — No changeset** · Process · PR files
The PR changes published code under `packages/aurora/src` but adds no changeset, so the change gets no version bump or changelog entry.
_Fix:_ Run `pnpm changeset`, pick the bump type and commit the generated `.changeset/*.md`.

</details>

### 💡 &nbsp; Improvements

| #   | Severity | Category      | Issue                                                                                                        | Location                                                                                                               |
| --- | -------- | ------------- | ------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| I1  | 🟢 Low   | UI/UX         | 401/403 on the detail page render an inline error instead of a Sign-in redirect or a page-level info Message | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId.tsx:65`                       |
| I2  | 🟢 Low   | UI/UX         | 401 copy says "Log in again to continue."; the writing rules require "Sign in"                               | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId.tsx:66`                       |
| I3  | 🟢 Low   | Code Quality  | Raw `<button>` for "Try Again" in the subnets error state instead of Juno `Button`                           | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:69`   |
| I4  | 🟢 Low   | Code Quality  | Active detail tab is kept in `useState`, not in the URL search params                                        | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:109`  |
| I5  | 🟢 Low   | Accessibility | Row action `PopupMenu` has no `PopupMenuToggle` trigger                                                      | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:56`      |
| I6  | 🟢 Low   | UI/UX         | Network status is shown as plain text instead of a `Badge`                                                   | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:43`      |
| I7  | 🟢 Low   | UI/UX         | Admin state is shown as all-caps `UP` / `DOWN`                                                               | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:46`      |
| I8  | 🟢 Low   | UI/UX         | Labels "Created At" / "Updated At" capitalise the preposition                                                | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:132`  |
| I9  | 🟢 Low   | Code Quality  | `useEffect` copies the `currentPage` prop into `inputPage` state                                             | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkListContainer.tsx:36` |
| I10 | 🟢 Low   | Performance   | `list` ignores Neutron pagination (`limit`/`marker`, next links), so a capped deployment silently truncates  | `packages/aurora/src/server/Network/routers/networksRouter.ts:44`                                                      |
| I11 | 🟢 Low   | Bug           | `NetworkSortKeySchema` allows `shared`, which isn't a documented Neutron network sort key                    | `packages/aurora/src/server/Network/types/network.ts:61`                                                               |
| I12 | 🟢 Low   | Test coverage | No tests for the new router, helpers or components (issue #1019 asks for complete testing coverage)          | PR files                                                                                                               |
| I13 | 🟢 Low   | UI/UX         | Project home page has no Networks card, though the sidebar now has a Networks entry                          | `packages/aurora/src/client/routes/_auth/projects/$projectId/index.tsx:87`                                             |
| I14 | 🟢 Low   | Docs          | The new `networks` service key isn't documented in the README or `.env.example` key lists                    | `packages/aurora/README.md:183`                                                                                        |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**I1 — 401/403 handled inline on the detail page** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId.tsx:65`
`packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId.tsx:65` maps `FORBIDDEN` and `UNAUTHORIZED` to descriptions that `NetworkLoadError` shows in the page. copilot-instructions B.6 asks for a redirect to Sign-in on 401 and a page-level info Message on 403. The `_auth` layout checks the session too, so in practice this mostly matters for a token that expires mid-session.
_Fix:_ On `UNAUTHORIZED`, redirect to Sign-in the way other routes do; on `FORBIDDEN`, show the page-level info Message.

**I2 — "Log in" wording in the 401 message** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId.tsx:66`
`packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId.tsx:66` reads "The session has expired. Log in again to continue." copilot-instructions B.19 and the Quick Reject list require "Sign in", not "Log in".
_Fix:_ Change the string to use "Sign in" and re-extract the catalogs (`pnpm check-i18n`).

**I3 — Raw `<button>` where Juno `Button` exists** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:69`
The subnets error `Status` at `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:69` uses a plain `<button onClick={() => refetch()}>`, so it gets no Juno styling or variant. copilot-instructions B.1 and the Quick Reject list reject raw HTML controls where a Juno equivalent exists. `$networkId.tsx` in this PR already uses Juno `Button`.
_Fix:_ Use Juno `Button` (for example `variant="primary"`) with the same `onClick`.

**I4 — Detail tab is lost on refresh** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:109`
`packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:109` keeps the active tab in `useState`, so a refresh or a shared link always opens Overview. copilot-instructions B.9 lists "Active tab" as state that must live in the URL (`tab`).
_Fix:_ Add a `tab` search param to the `$networkId` route's `validateSearch` and read and write it with `useSearch`/`navigate`.

**I5 — `PopupMenu` without the required `PopupMenuToggle`** · Accessibility · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:56`
`packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:56` renders `<PopupMenu><PopupMenuOptions>` with the default toggle, and `PopupMenuToggle` isn't imported. copilot-instructions B.14 requires `<PopupMenuToggle as="div"><Button icon="moreVert" /></PopupMenuToggle>` as the trigger, for a consistent accessible button.
_Fix:_ Wrap the trigger in `<PopupMenuToggle as="div"><Button icon="moreVert" /></PopupMenuToggle>`, as the other list rows do.

**I6 — Status without a `Badge`** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:43`
The list row at `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:43` renders `network.status` as plain text, and the detail Overview at `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:116` does the same. copilot-instructions B.1 asks for status indicators to use `Badge`.
_Fix:_ Render the status as a Juno `Badge` with a variant that matches the state (for example success for `ACTIVE`, danger for `ERROR`).

**I7 — All-caps admin state strings** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:46`
`packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:46` and `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:117` translate `admin_state_up` as `` t`UP` `` / `` t`DOWN` ``. copilot-instructions B.19 says text is never all-caps.
_Fix:_ Use "Up" / "Down" (or "Enabled" / "Disabled") in both places.

**I8 — Title case: "Created At" / "Updated At"** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:132`
`packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:132` and the next line use `` t`Created At` `` and `` t`Updated At` ``. copilot-instructions B.19 keeps short prepositions like "at" lowercase in title case.
_Fix:_ Use "Created at" / "Updated at".

**I9 — Prop-to-state sync through `useEffect`** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkListContainer.tsx:36`
`packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkListContainer.tsx:36` runs `setInputPage(currentPage.toString())` in a `useEffect` whenever `currentPage` changes. That costs an extra render per page change, and copilot-instructions A.1 asks to flag such syncs.
_Fix:_ Derive the value during render (keep the previous prop in state and reset when it changes), or remount the input with `key={currentPage}`.

**I10 — No pagination on the Neutron networks list** · Performance · `packages/aurora/src/server/Network/routers/networksRouter.ts:44`
`packages/aurora/src/server/Network/routers/networksRouter.ts:44` makes one `GET /v2.0/networks` call with no `limit`/`marker`, and the response schema has no `networks_links`. The [Neutron pagination reference](https://docs.openstack.org/api-ref/network/v2/#pagination) says a deployment can cap list size, and then returns next links. With such a cap, only the first page arrives, with no sign it was cut, and the client-side search, status filter and page count work only on that page. By default (pagination off) Neutron returns everything, so this only hits deployments that enable it.
_Fix:_ Follow `networks_links` `next` until it runs out (or page with `limit`/`marker`) and add `networks_links` to the response schema.

**I11 — `shared` is not a Neutron sort key** · Bug · `packages/aurora/src/server/Network/types/network.ts:61`
`packages/aurora/src/server/Network/types/network.ts:61` allows `name`, `status`, `admin_state_up` and `shared`, under a comment saying they're supported by Neutron. The [list-networks reference](https://docs.openstack.org/api-ref/network/v2/#list-networks) limits sort keys to `admin_state_up`, `availability_zone_hints`, `id`, `mtu`, `name`, `status`, `tenant_id`, `project_id`. `sort_key=shared` is forwarded as-is, so Neutron may reject the request or ignore the sort. The UI doesn't offer this sort today, so nothing breaks yet.
_Fix:_ Remove `shared` from the enum (or sort by it in the BFF) and correct the comment.

**I12 — New BFF and pages ship without tests** · Test coverage · PR files
Issue #1019 lists complete testing coverage (unit, integration, E2E) among its acceptance criteria. The PR adds no tests for `networksRouter.ts`, `networkHelpers.ts`, the types or any new component; only `buildNavSections.test.ts` changed. The "I have added tests" box in the PR body is unticked. The `project_id` bug in CR1 is the kind of thing a router test checking the query parameters would catch.
_Fix:_ Add vitest tests for the router (query parameters, error mapping), the helpers and the list/detail components, following the existing `securityGroupRouter.test.ts` and route tests.

**I13 — Networks missing from the project home cards** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/index.tsx:87`
`packages/aurora/src/client/routes/_auth/projects/$projectId/index.tsx:87` and the cards around it build Network cards for security groups, floating IPs and routers, gated by `isEnabled`, but there's none for `networks`. `buildNavSections` now adds Networks to the sidebar, so the home page and the sidebar disagree.
_Fix:_ Add a Networks card gated by `isEnabled("networks")` next to the other Network cards.

**I14 — `networks` service key not documented** · Docs · `packages/aurora/README.md:183`
The PR gates the new nav entry with `isEnabled("networks")`, which makes `networks` part of the public `enabledServices` contract. The service-key lists in `packages/aurora/README.md:183` and `packages/aurora/README.md:210` (the source of truth for `AuroraApp` props) and the comment at `apps/dashboard/.env.example:11` don't include it. An operator who sets `VITE_ENABLED_SERVICES` from the documented list hides the new Networks page without knowing. `routers` was already missing from these lists.
_Fix:_ Add `networks` (and the missing `routers`) to both README lists and the `.env.example` comment.

</details>

---

## Solution Overview

<details>
<summary><strong>What was done</strong></summary>

Draft PR adding a read-only Neutron Networks view under the Network section: a BFF router (`network.networks.list`, `getById`, `listSubnets`), a list page, a detail page with Overview and Subnets tabs, and a sidebar entry. Phase 1 (`P1`) of epic #1019. Create/update/delete, tags and Ports are not included.

**Server** (`packages/aurora/src/server/Network/`): Zod schemas in `types/network.ts`, helpers in `helpers/networkHelpers.ts` (error handlers, a mapper that derives `external` and `subnet_count`, a BFF-side status filter), and `routers/networksRouter.ts` with three `projectScopedProcedure` queries, wired into `routers/index.ts`.

**Client** (`packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/`): a layout route `networks.tsx`, a list route `index.tsx` with URL-driven search, sort and page state, a detail route `$networkId.tsx` with its own error mapping and retry, and `-components/` (`NetworksList`, `NetworkListContainer`, `NetworkTableRow`, `NetworkDetailsView`).

**Navigation/i18n/generated**: a "Networks" item at the top of the Network nav section in `buildNavSections.ts` (test expectations updated), plus new en/de message catalog entries and regenerated `routeTree.gen.ts`.

**CI**: 18 jobs pass, 4 are skipped, none fail or are pending on the head commit. The PR is a draft. The body leaves the test checkboxes unticked, and the diff has no tests for the new router, helpers or components. Only the `buildNavSections` test was updated.

</details>

<details>
<summary><strong>How it is implemented</strong></summary>

**BFF list.** `list` forwards `project_id`, `name`, `admin_state_up`, `shared`, `sort_key` and `sort_dir` to Neutron (everything except `searchTerm` and `status`). `searchTerm` (over id, name and description) and `status` are applied in the BFF after the full list is fetched. Results are mapped through `toNetworkListItem`, so the UI never sees `router:external`.

```ts
list: projectScopedProcedure
  .input(NetworkQueryParametersSchema)
  .query(async ({ input, ctx }): Promise<NetworkListItem[]> => {
    return withErrorHandling(async () => {
      const { searchTerm, status, ...openstackFilters } = input
      const network = getNetworkService(ctx)

      const queryParams = appendQueryParamsFromObject(openstackFilters)
      const response = await requestOrThrow(
        () => network.get(withQuery(NETWORKS_BASE_URL, queryParams)),
        NetworkErrorHandlers.list
      )

      const data = await response.json()
      const { networks } = parseOrThrow(NetworkListResponseSchema, data, "networksRouter.list")

      const filtered = filterBySearchParams(filterNetworksByBffParams(networks, { status }), searchTerm, [
        "id",
        "name",
        "description",
      ])

      return filtered.map(toNetworkListItem)
    }, "list networks")
  }),
```

The mapper renames `router:external` to `external` and replaces the subnets array with a count, but keeps `subnets` too.

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

**Subnets tab.** `listSubnets` calls `/v2.0/subnets` filtered by `network_id`, with `fields` limited to what the table shows. The ID is validated with `validateAndEncodeResourceId`, but the encoded value is discarded because the ID goes in the query string (``packages/aurora/src/server/Network/routers/networksRouter.ts:89``).

```ts
listSubnets: projectScopedProcedure
  .input(NetworkIdInputSchema)
  .query(async ({ input, ctx }): Promise<NetworkSubnet[]> => {
    return withErrorHandling(async () => {
      const { network_id } = input
      const service = getNetworkService(ctx)

      // Validates the ID; it is sent as a query param (encoded by URLSearchParams), not as a path segment
      validateAndEncodeResourceId(network_id, "Network")

      const params = appendQueryParamsFromObject({
        network_id,
        fields: ["id", "name", "cidr", "ip_version", "gateway_ip", "enable_dhcp"],
      })
      const response = await requestOrThrow(
        () => service.get(withQuery(SUBNETS_BASE_URL, params)),
        NetworkErrorHandlers.listSubnets,
        network_id
      )

      const data = await response.json()
      return parseOrThrow(NetworkSubnetListResponseSchema, data, "networksRouter.listSubnets").subnets
    }, "list network subnets")
  }),
```

**List page.** `NetworksList.tsx` uses the React 19 `use()` + Suspense pattern. The URL is the source of truth for search, sort and page. `useDeferredValue` keeps the previous list on screen while a new query loads. A FORBIDDEN response is turned into an inline `listError` instead of throwing. Pagination is client-side, 50 rows per page, with the page clamped to the total.

```tsx
const createNetworksPromise = (
  client: TrpcClient,
  project: string,
  sortBy: NetworkSortKey,
  sortDirection: "asc" | "desc",
  searchTerm: string
): Promise<NetworksResult> => {
  return client.network.networks.list
    .query({ project_id: project, sort_key: sortBy, sort_dir: sortDirection, searchTerm: searchTerm || undefined })
    .then((networks) => ({ networks, listError: undefined }))
    .catch((err: unknown) => {
      if (err instanceof TRPCClientError && err.data?.code === "FORBIDDEN") {
        return { networks: [], listError: err.message }
      }
      throw err
    })
}
```

**Detail page.** The loader only resolves the page title and swallows errors. The component runs its own `getById` query, so it can map the tRPC error code to a title and description and offer Try Again for transient codes only. A route `errorComponent` handles render-time errors.

```tsx
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
```

**Overview tab.** `NetworkDetailsView` shows name, ID and project ID (both with copy), status, admin state, shared, external, MTU, port security and subnet count. Tags and created/updated timestamps are shown only when present. The Subnets tab fetches lazily.

[[code:packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx | const overviewItems: DetailItem[] = [ | 22]]

</details>

<details>
<summary><strong>What it affects (blast radius)</strong></summary>

**Contract.** This adds a new tRPC surface, `network.networks.{list,getById,listSubnets}`, to the `network` router tree. `packages/aurora/src/server/Network/routers/index.ts` is its only server-side hook. Nothing outside the PR consumes these procedures yet. Nothing existing is renamed or removed, so this is additive. `network.networks` is carried by the `AuroraRouter` type, which is public. Because the `list` and `getById` return type is `NetworkListItem`, the shape is now part of that type.

**New service key.** `"networks"` is a new key for `enabledServices` / deny lists. It is checked with `isEnabled("networks")` in `buildNavSections.ts`.

**Permissions.** `network:networks:read` and `network:networks:list` already exist in `packages/aurora/src/server/Network/routers/permissionRouter.ts:19-20`. Neither the new procedures nor the UI call `canUser`, so the existing mappings are not enforced on this page. The procedures rely only on Neutron's own authorization.

**Other callers left unchanged.** (1) The project home page builds its Network service cards from `isEnabled(...)` checks for `securitygroups`, `floatingips` and `routers` in `packages/aurora/src/client/routes/_auth/projects/$projectId/index.tsx`. It has no Networks card, so the sidebar and home page now disagree. (2) `packages/aurora/README.md` lists the service keys at lines 183 and 210 without `networks`. It also omits `routers`, so it was already behind. (3) There is no BFF design doc for Networks, unlike `packages/aurora/docs/0010_routers_bff.md` for Routers.

**Shared code reused, not changed.** `ErrorHandler`, `requestOrThrow`, `filterBySearchParams` and `appendQueryParamsFromObject` are used unmodified.

</details>

---

## QA Test Plan

<details>
<summary><strong>Core Path</strong></summary>

1. Open a project whose catalog has the Neutron `network` service. Check that Network in the sidebar now lists Networks first, ahead of Security Groups, Floating IPs and Routers.
2. Click Networks. The list loads with the default sort Name ascending, and the columns are Name/ID, Status, Shared, MTU, Admin State, Subnets and Port Security.
3. Change sort to Status and flip the direction. The list reorders and the URL gets `sortBy` and `sortDirection` params, with no history entry added.
4. Type in the search box. After about 500 ms the list filters by id, name or description. The `search` param appears in the URL and the previous list stays visible while loading.
5. With more than 50 networks, use pagination. The `page` param updates and a browser Back returns to the previous page.
6. Click a row, or use the Show Details row action. The detail page opens with the network name as breadcrumb and page title.
7. On the Overview tab, check the status, MTU, admin state, shared, external, port security and subnet count values against `openstack network show`. Copy the ID and the project ID.
8. Switch to the Subnets tab. Check the name, CIDR, IP version, gateway IP and DHCP columns against `openstack subnet list --network <id>`.
9. Use the breadcrumb or Back to Networks to return to the list.

</details>

<details>
<summary><strong>Edge Cases</strong></summary>

- Network with an empty name: the list and detail header fall back to the ID (`$networkId.tsx` `network.name || network.id`), and Overview shows "—" for Name.
- Network with a null MTU or null port security: Overview shows "—" (`NetworkDetailsView.tsx` `network.mtu ?? "—"` and the port security branch).
- Network with no subnets: the Subnets tab shows the "No Subnets" empty state, and Overview shows a subnet count of 0.
- Subnet with a null gateway, a missing CIDR or an unset DHCP flag: the cells show "–" (`NetworkDetailsView.tsx` `subnet.cidr || "–"`).
- Subnets request fails: the tab shows an inline error with Try Again, while the Overview tab still works.
- User not allowed to list: a FORBIDDEN response renders "Failed to Load Networks" inline, not the error boundary (`NetworksList.tsx` `err.data?.code === "FORBIDDEN"`). Any other error shows the boundary with Try Again.
- Detail page for an unknown or foreign network ID: 404 shows "Network Not Found" without Try Again. 403 and 401 show their own messages. 5xx, timeout and network failures show Try Again (`$networkId.tsx` `RETRYABLE_TRPC_CODES`).
- Hand-edit the URL with an invalid `sortBy` or `page`, such as `sortBy=foo` or `page=0`. Each invalid param is dropped and the rest are kept (`index.tsx` `validateSearch`).
- Page beyond the last page after filtering, or Back/Forward between filtered and unfiltered lists: the page resets to 1 once the current query has resolved (`NetworksList.tsx` `onPageChange(1)`).
- Switch projects while on the list: the list remounts, so the previous project's rows do not show (`index.tsx` `key={projectId}`).
- Status filter and search run on the full fetched list. Check behaviour against a project with a very large number of networks, since there is no server-side pagination.
- Hide `networks` through `enabledServices` or the deny list: the nav item disappears, but the route is still reachable by URL and the project home page is unaffected.
- Search is case-insensitive over id, name and description, and a whitespace-only term should behave like no search (`hasSearch` trims it, the schema `.trim()`s `searchTerm`).
- Project that uses a shared or external network owned by another project (e.g. the provider `public` network): it doesn't appear in the Networks list, because `list` sends `project_id` to Neutron (CR1).
- Admin token on the Networks list: check that only the project's own and shared networks are listed, not every project's (CR1).
- A `list` call with `sort_key=shared`: Neutron rejects it or ignores the sort (I11).

</details>

---

## Checked and dismissed

<details>
<summary><strong>Candidates scored below 50 (8)</strong></summary>

| Score | Candidate                                                                                                                                         | Location                                                                                                        | Why                                                                                                                                                                                                 |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 25    | Raw &lt;div&gt; elements are used as layout wrappers (break-all wrapper in DetailsList, relative wrapper around ErrorBoundary in Networks) where… | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:223` | The &lt;div className="relative"&gt; (NetworksList.tsx:223) and &lt;div className="break-all"&gt; (NetworkDetailsView.tsx:38) are plain styling or positioning wrappers.                            |
| 25    | A useEffect corrects an out-of-range page by calling onPageChange(1).                                                                             | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:97`  | The effect at NetworksList.tsx:97-99 triggers a URL navigation (onPageChange(1)) as a side effect, which cannot be done during render.                                                              |
| 25    | status filter is applied BFF-side although Neutron documents a server-side `status` filter for list networks; combined with no pagination,…       | `packages/aurora/src/server/Network/routers/networksRouter.ts:39`                                               | Neutron does document a server-side status filter, but filtering BFF-side gives the same result on the returned set; the only effect is an inaccurate comment, and the pagination interaction is…   |
| 25    | listSubnets sends fields and network_id correctly but lists subnets with no pagination and under the same owner-only default policy, so…          | `packages/aurora/src/server/Network/routers/networksRouter.ts:92`                                               | listSubnets filters only by network_id (lines 91-94), with no project_id filter, so visibility is left to Neutron's policy and RBAC; I can't confirm that subnets of shared networks are hidden in… |
| 0     | Acceptance criterion partly met: tRPC BFF is implemented with complete Zod schema validation for Networks.                                        | `packages/aurora/src/server/Network/types/network.ts:9`                                                         | Create/update/delete schemas are outside the PR's stated read-only scope (pr-body.md); the in-scope validation is present.                                                                          |
| 0     | Acceptance criterion partly met: Users can list, view, create, update, and delete networks (P1 & P2).                                             | `packages/aurora/src/server/Network/routers/networksRouter.ts:35`                                               | List and view are implemented; create/update/delete are explicitly out of the stated read-only scope.                                                                                               |
| 0     | Acceptance criterion partly met: Advanced properties like MTU, Admin State, and Shared status are visible and manageable where appropriate…       | PR files                                                                                                        | MTU, admin state and shared are visible, and the PR body limits this PR to the read-only part, so the 'manageable' half is out of scope.                                                            |
| 0     | Acceptance criterion partly met: Comprehensive error handling provides user-friendly feedback for Neutron errors (e.g., preventing deletion…      | `packages/aurora/src/server/Network/helpers/networkHelpers.ts:8`                                                | Read-path errors are handled (ErrorHandler in the BFF, error mapping on the detail page).                                                                                                           |

</details>

---

_Analyzed 2026-10-23 · commit `0a594e9e` · read-only · skill: review-and-comment-pr_

<!-- related:auto — generated from pr/issue properties by tools/update-related.py; do not edit by hand -->
## Related

- plan · 2026-10-12 · [2026-10-12-networks-epic-1019-analysis](../../plans/2026-10-12-networks-epic-1019-analysis.md)
- plan · 2026-10-12 · [2026-10-12-networks-phase-1-read-operations](../../plans/2026-10-12-networks-phase-1-read-operations.md)
- pr-report · 2026-10-17 · [1386-network-and-verify-do-not-merge](1386-network-and-verify-do-not-merge.md)
- pr-report · 2026-10-30 · [1385-neutron-networks-bff-read-only-networks-page](1385-neutron-networks-bff-read-only-networks-page.md)
