---
type: pr-report
date: 2026-10-16
status: open
pr: [1386]
issue: [1019]
author: TilmanHaupt
branch: hack-valid
commit: e6b1e69
---

# PR #1386: feat(core): network and verify DO NOT MERGE

**Author:** @TilmanHaupt · **State:** 🟡 Draft · **Base:** `main` ← `hack-valid`
**Size:** 47 files, +4361 / −5 · **Created:** 2026-10-16 · [View on GitHub](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1386)

---

## PR Review Report

### ⚖️ &nbsp; Verdict

> Recommendation: **🔴 Request Changes** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **Low**
>
> This is a draft titled "DO NOT MERGE" that bundles two unrelated things: a Neutron Networks BFF with read-only list/detail pages, and 29 `.claude/` agent/skill files made trackable by a `.gitignore` change. The networks code has real bugs: the tag-filter key map is passed in the wrong argument shape, subnet lookup failures show as "No subnets", and a search with no results hides the search box. It also ships a Create button that only does `console.log`, and it collides head-on with open PRs #1385/#1383, which add the same files and the same `network.networks` tRPC key. CI's `test` job fails because `buildNavSections.test.ts` was not updated for the new nav entry. Acceptance was graded against the networks epic #1019 (Phase 1), which the PR does not link.

### 🔧 &nbsp; Required Changes

| #    | Severity    | Category     | Issue                                                                                          | Location                                                 |
| ---- | ----------- | ------------ | ---------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| CR1  | 🟡 Moderate | Bug          | Tag-filter key map passed as `options`, so `tags_any`/`not_tags`/`not_tags_any` are never renamed | `packages/aurora/src/server/Network/routers/networksRouter.ts:106` |
| CR2  | 🟡 Moderate | Bug          | Any subnet lookup failure is swallowed and shown as "No Subnets"                                | `packages/aurora/src/server/Network/routers/networksRouter.ts:53` |
| CR3  | 🟡 Moderate | UI/UX        | A search with no results hides the SearchInput, so the search can't be cleared                 | `…/network/networks/-components/NetworksList.tsx:99`     |
| CR4  | 🟡 Moderate | Code Quality | "Create Network" button is a `console.log` stub behind a hard-coded `canCreate = true`         | `…/network/networks/-components/NetworksList.tsx:54`     |
| CR5  | 🟡 Moderate | UI/UX        | List view lacks the pagination and Status/Shared filters that epic #1019 Phase 1 requires        | `…/network/networks/-components/NetworksList.tsx:30`     |
| CR6  | 🟡 Moderate | Bug          | `list` makes one Neutron GET and ignores `networks_links`, so a page-size cap truncates it silently | `packages/aurora/src/server/Network/routers/networksRouter.ts:108` |
| CR7  | 🟡 Moderate | Performance  | Detail route fetches the network twice (loader + `useQuery`); the component's error branches never run on the first load | `…/network/networks/$networkId/index.tsx:20`             |
| CR8  | 🟡 Moderate | UI/UX        | List-page zones deviate from B.2 (Create in its own Stack, raw `<div>`, extra Refresh toolbar)  | `…/network/networks/-components/NetworksList.tsx:120`    |
| CR9  | 🟡 Moderate | Code Quality | `.gitignore` makes `.claude/skills` and `.claude/agents` trackable; 29 tooling files ship in a feature PR | `.gitignore:12`                                          |
| CR10 | 🟡 Moderate | Code Quality | Add/add conflicts with open #1385 and #1383, which register the same `network.networks` key with a different contract | `packages/aurora/src/server/Network/routers/index.ts:17` |
| CR11 | 🟡 Moderate | Code Quality | Unrelated, half-applied `ROUTE_ID` inlining in the Routers detail route conflicts with #1377    | `…/network/routers/$routerId.tsx:58`                     |
| P1   | —           | Process      | Draft, and titled "DO NOT MERGE"                                                               | PR state                                                 |
| P2   | —           | Process      | PR body is just "Test-PR": template unused and no issue linked                                 | PR body                                                  |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**CR1 — Tag-filter key map never applied** · Bug · `packages/aurora/src/server/Network/routers/networksRouter.ts:106`
`appendQueryParamsFromObject(source, options?: AppendQueryParamsOptions)` reads `const { keyMap } = options ?? {}` (`server/helpers/queryParams.ts:31`). The router passes the bare map instead, so `keyMap` is `undefined` and the `tags_any → tags-any` / `not_tags → not-tags` / `not_tags_any → not-tags-any` renames never happen. Neutron's documented filter names are the hyphenated ones, so these three filters do nothing. No UI uses them yet, which keeps the impact contained, and no test covers the list query string.
_Fix:_ `appendQueryParamsFromObject(neutronParams, { keyMap: LIST_NETWORKS_QUERY_KEY_MAP })`, plus a router test that asserts the outgoing URL.

**CR2 — Subnet lookup failures look like "no subnets"** · Bug · `packages/aurora/src/server/Network/routers/networksRouter.ts:53`
`fetchSubnetDetails` returns `[]` on a non-OK response (`:53`), and its bare `catch` (`:56`) does the same for network errors and Zod parse failures. `NetworkDetailsView.tsx:84` then renders "No Subnets — This network has no subnets…". A 403 or 5xx on `/v2.0/subnets`, or one unexpected field, makes the page claim something false. The JSDoc ("so callers can handle missing subnet details gracefully") promises something the view can't do, because it can't tell failure from empty.
_Fix:_ return a distinguishable result (e.g. `subnet_details: null` + `subnet_error`), or let the error propagate, and render a scoped error in the Subnets section.

**CR3 — Empty search result removes the search box** · UI/UX · `…/network/networks/-components/NetworksList.tsx:99`
The `networks.length === 0` branch returns before the toolbar that holds `SearchInput` (`:131`). After a search with no hits, the page says "No networks match your search. Clear the search to view all networks." but offers no way to do that short of leaving the page. B.6 says the "no filter results" state should suggest clearing filters, which assumes the user can.
_Fix:_ always render Zone 2 (the search toolbar) and show the `no-matches` `Status` in place of the DataGrid only.

**CR4 — Placeholder Create button with no permission check** · Code Quality · `…/network/networks/-components/NetworksList.tsx:54`
`const canCreate = true // Placeholder` gates a primary "Create Network" button whose handler is `console.log("Create network clicked")` (`:58`). This hits two Quick Reject items: "'Create' button rendered without permission check" and "UI control shown before permissions are resolved (not fail-closed)". The `network:networks:create` key already exists in the Network permission router and is unused. The button is also missing exactly where it would matter: the empty state says "Networks can be created through the API or CLI", while B.6 says a no-data state should suggest creating.
_Fix:_ drop the button until the create modal exists, or gate it on a `canUser` check that defaults to `false`. Remove the `console.log`.

**CR5 — Epic #1019 Phase 1 list requirements not met** · UI/UX · `…/network/networks/-components/NetworksList.tsx:30`
The PR body links no issue. At the user's request this was graded against epic #1019, which the changeset calls "Phase 1". That phase requires "(UI) Create Networks List View with DataGrid, pagination, and filters (Name, Status, Shared)". The list has only a name/description search (`:30-31`, `:131`): there is no pagination, no Status filter and no Shared filter. The other Phase 1 items are present: `list`/`getById` with Zod schemas, a detail page with Status/MTU/Admin State, and copy-to-clipboard IDs.
_Fix:_ add pagination and Status/Shared filters (URL-backed, see I1), or narrow the stated scope and link the sub-issue it actually closes.

**CR6 — List can be silently truncated** · Bug · `packages/aurora/src/server/Network/routers/networksRouter.ts:108`
`list` makes a single `GET v2.0/networks`, and `NetworkListResponseSchema` drops `networks_links`. The Neutron API reference says "list operations will return a maximum number of items at a time" when the deployment configures a limit, with `next` links for the rest (https://docs.openstack.org/api-ref/network/v2/index.html, Pagination). On such a deployment the page shows only the first page, and the BFF-side search runs on that subset. Precedent: no sibling Network router follows Neutron's `next` links either, so expect pushback, but the Routers list from #1355 does paginate.
_Fix:_ follow `networks_links` `next` until it runs out (or pass `limit`/`marker` through), and add UI pagination per CR5.

**CR7 — Double fetch on the detail page** · Performance · `…/network/networks/$networkId/index.tsx:20`
The loader calls `context.trpcClient?.network.networks.getById.query(...)` through the raw client, outside the Query cache, only to read the name. The component then calls `trpcReact.network.networks.getById.useQuery(...)` (`:62`). Every visit costs two network GETs and two subnet lookups. Because the loader throws on error, the parent `errorComponent` (`networks.tsx:34`) handles first-load failures, and the component's `isError` and "Network Not Found" branches only run on a later refetch. Precedent: a maintainer deferred the same loader pattern for Routers on #1355.
_Fix:_ prefetch into the cache from the loader (`ensureQueryData` via the tRPC utils), or drop the loader fetch and derive the title from the query.

**CR8 — List-page zone structure** · UI/UX · `…/network/networks/-components/NetworksList.tsx:120`
B.2 Reject: "any structure that mixes zones or skips Zone 2". Zone 1 here is a bare `<Stack distribution="end">` holding only the Create button (no `pb-2`, no sort control, not `distribution="between"`). Everything is wrapped in a raw `<div>` (Quick Reject: "Raw HTML element … where a Juno component exists"). A second `DataGridToolbar` with an item count and a Refresh button (`:144-153`) matches none of the defined zones. Copilot raised the same Zone 1 layout on #1360 (`SecurityGroupsList.tsx`).
_Fix:_ follow the B.2 structure: Zone 1 `Stack distribution="between" className="pb-2"` (sort left, primary action right), then Zone 2 search, then the grid.

**CR9 — Agent tooling made trackable and shipped** · Code Quality · `.gitignore:12`
`.claude` becomes `.claude/*` + `!.claude/skills/` + `!.claude/agents/`, and the PR adds 29 files (about 3,000 lines) of skills and agents. One of them, `sap_juno_lookup.md`, is duplicated under `.claude/agents/` and `.claude/skills/verifyUI/agents/`. The PR also ignores `tmp/aurora-reviews/`, `screenshots/` and `.playwright-mcp/`. `.claude` has been ignored since the initial repo setup. Flipping that inside a feature PR changes repo policy as a side effect, and every contributor's own local `.claude/skills` would start showing in `git status`. The security pass found no secrets or unsafe commands in these files.
_Fix:_ move the `.claude/` files and the `.gitignore` change to a separate PR where the team can decide on shared agent tooling.

**CR10 — Collides with open networks PRs** · Code Quality · `packages/aurora/src/server/Network/routers/index.ts:17`
`git merge-tree` against #1385 (`9ed4250`) and #1383 (`3e32ab0`) reports add/add conflicts in `networksRouter.ts`, `types/network.ts`, `networkHelpers.ts`, `NetworksList.tsx`, `networks.tsx` and `networks/index.tsx`, plus content conflicts in `routeTree.gen.ts` and the locale files. All three register `network.networks`, and #1385 adds `setTags`/`listSubnets`, so the procedure set differs. Only one can land as-is.
_Fix:_ settle which PR owns Networks; rebase this one onto it or close it.

**CR11 — Unrelated Routers route change** · Code Quality · `…/network/routers/$routerId.tsx:58`
The PR inlines the route-id string in `useParams` (`:58`) and `createFileRoute` (`:117`), but `const ROUTE_ID` is still declared (`:11`) and used (`:146`). The file now mixes the constant and two copies of the literal. It is unrelated to Networks and conflicts with open PR #1377 (Ports). #1385 claims the TanStack route generator needs the literal in `createFileRoute`. If that holds, the `createFileRoute` site is justified, but the `useParams` edit isn't.
_Fix:_ keep only the `createFileRoute` change if it's needed for generation, revert `:58`, and land it once rather than on every networking branch.

**P1 — Draft / "DO NOT MERGE"** · Process · PR state
The PR is a draft and its title says not to merge. The findings above apply if any of this code is meant to land through it.
_Fix:_ mark it ready only once it is the intended delivery vehicle, and drop "DO NOT MERGE" from the title.

**P2 — No description, no linked issue** · Process · PR body
The body is "Test-PR". The repo template is unused, there are no testing instructions, and no issue is linked. Acceptance above was graded against epic #1019 at the user's request. That does not make the PR link it.
_Fix:_ fill in the PR template and add `Part of #1019` (plus the sub-issue it closes).

</details>

### 💡 &nbsp; Improvements

| #   | Severity   | Category     | Issue                                                                  | Location                                                   |
| --- | ---------- | ------------ | ---------------------------------------------------------------------- | ---------------------------------------------------------- |
| I1  | 🟢 Low     | Code Quality | Search term kept in `useState` instead of URL search params              | `…/network/networks/-components/NetworksList.tsx:30`       |
| I2  | 🟢 Low     | UI/UX        | Network status rendered as plain text, not a `Badge`                    | `…/network/networks/-components/NetworksList.tsx:172`      |
| I3  | 🟢 Low     | Docs         | Changeset describes review-round history and claims things not in the code | `.changeset/networks-management-phase1.md`                 |
| I4  | 🟢 Low     | Code Quality | `NetworkSortKeySchema` allows `shared`, which isn't a documented Neutron sort key | `packages/aurora/src/server/Network/types/network.ts:114`  |
| I5  | 🟢 Low     | Code Quality | `update` forwards `provider:*` attributes most plug-ins can't update      | `packages/aurora/src/server/Network/routers/networksRouter.ts:203` |
| I6  | 🟢 Low     | UI/UX        | 403 handled inline in the list's error `Status`                         | `…/network/networks/-components/NetworksList.tsx:79`       |
| I7  | 🟢 Low     | UI/UX        | Placeholder "Search by name" while search matches name or description   | `…/network/networks/-components/NetworksList.tsx:139`      |
| I8  | ⚪ Trivial | Code Quality | Import order (B.13) and `@cloudoperators/juno-ui-components/index` path   | `…/network/networks/$networkId/index.tsx:1`                |
| I9  | ⚪ Trivial | Docs         | JSDoc says `getById` adds "subnet and port details"; it adds no ports   | `packages/aurora/src/server/Network/types/network.ts:209`  |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**I1 — Search state not in the URL** · Code Quality · `…/network/networks/-components/NetworksList.tsx:30`
Quick Reject: "URL-worthy state held in `useState` instead of search params" (B.9). The submitted term is lost on reload and on Back from the detail page. The `routers/` and `floatingips/` list routes use `validateSearch`.
_Fix:_ add `validateSearch` to `networks/index.tsx` and read/write `search` through `useSearch`/`navigate`.

**I2 — Status without Badge** · UI/UX · `…/network/networks/-components/NetworksList.tsx:172`
B.1 lists "Status indicators | `Badge`", but `{network.status}` is plain text here and in `NetworkDetailsView.tsx`. On #1355 a maintainer accepted plain text "across all lists in a separate change", so expect pushback.
_Fix:_ render status as a `Badge`, or leave it for the cross-list change.

**I3 — Changeset text** · Docs · `.changeset/networks-management-phase1.md`
This is public release-note text, but its bullets read like a review log ("now", "Remove redundant query key mapping in networksRouter"). The map is still defined (`networksRouter.ts:26`) and passed (`:106`). The changeset also claims an "ErrorBoundary wrapper", but the code uses TanStack's `errorComponent`.
_Fix:_ describe the user-facing feature only.

**I4 — Undocumented sort key** · Code Quality · `packages/aurora/src/server/Network/types/network.ts:114`
The API reference says "The sort keys are limited to: admin_state_up, availability_zone_hints, id, mtu, name, status, tenant_id, project_id" (https://docs.openstack.org/api-ref/network/v2/index.html#list-networks). The schema accepts `shared` and omits `availability_zone_hints`. No UI sorts yet.
_Fix:_ align the enum with the documented list.

**I5 — Provider attributes on PUT** · Code Quality · `packages/aurora/src/server/Network/routers/networksRouter.ts:203`
The API reference says "Most Networking plug-ins (e.g. ML2 Plugin) and drivers do not support updating any provider related attributes" (https://docs.openstack.org/api-ref/network/v2/index.html#update-network). They are only sent when a caller supplies them, and nothing calls `update` yet.
_Fix:_ drop `provider:*` from `NetworkUpdateRequestSchema` unless a real use case needs them.

**I6 — Inline 403** · UI/UX · `…/network/networks/-components/NetworksList.tsx:79`
B.6 Reject: "a 401/403 handled inline instead of via redirect / page-level info Message". Here FORBIDDEN becomes the body of an error `Status` that has a Retry button.
_Fix:_ for FORBIDDEN, show the page-level info `Message` with the standard 403 copy and no Retry.

**I7 — Search placeholder understates the search** · UI/UX · `…/network/networks/-components/NetworksList.tsx:139`
The BFF filter matches `name` or `description` (`networksRouter.ts:70-76`). Its comment also calls this "client-side search", although it runs in the BFF.
_Fix:_ use a placeholder like "Search by name or description" and fix the comment.

**I8 — Import order / path** · Code Quality · `…/network/networks/$networkId/index.tsx:1`
Juno comes before router/lingui, `trpcReact` comes after client imports, and the Juno import uses the `/index` subpath (also in `compute/flavors/$flavorId.tsx:12`). `NetworksList.tsx` likewise imports `trpcReact` after Juno.
_Fix:_ reorder per B.13 and import from `@cloudoperators/juno-ui-components`.

**I9 — JSDoc mentions ports** · Docs · `packages/aurora/src/server/Network/types/network.ts:209`
`NetworkDetails` has only `subnet_details`, and `getById` fetches no ports.
_Fix:_ "enriched with subnet details".

</details>

---

## Solution Overview

<details>
<summary><strong>What was done</strong></summary>

The PR bundles two unrelated pieces of work, built up over 39 commits.

**Networks (Neutron) — BFF.** A new `networksRouter` is mounted as `network.networks` with `list`, `getById`, `create`, `update` and `delete`, all on `projectScopedProcedure`. It comes with Zod schemas in `types/network.ts` and resource-specific error handlers in `helpers/networkHelpers.ts` built on the existing `ErrorHandler`. `list` forwards Neutron filters and then applies a BFF-side `searchTerm` over name and description. `getById` adds `subnet_details` from one batched `GET /v2.0/subnets?id=…`. The three write procedures have no UI caller yet.

**Networks — UI.** A `networks` layout route with an `errorComponent`, a list page, a detail page, and a "Networks" entry first in the Network section of the side nav (service key `networks`). The list shows Name, ID (copyable), Status, Admin State, Shared and External, and offers a submit-on-Enter search, an item count, a Refresh button and a placeholder Create button. The detail page shows network info, a subnets table (CIDR, IP version, gateway, allocation pools, DHCP) and, when present, provider attributes. Translations are added to `en`/`de` `.po` files. The new `de` entries have an empty `msgstr` (untranslated).

**Unrelated changes.** The Routers detail route inlines its route-id literal at two sites. The `.gitignore` change makes `.claude/skills` and `.claude/agents` trackable, and the PR adds 29 files there: `aurora-bff-review`, `aurora-ui-review` (including a `build-datagrid` sub-skill), `security-and-hardening`, `verify`, `verifyUI` and a `sap_juno_lookup` agent. It also ignores local screenshot/review output folders.

**Release.** It adds a `minor` changeset for `@cobaltcore-dev/aurora` ("Add Networks Management foundation").

**CI on `e6b1e69`.** Build, lint, typecheck, format, check-i18n and licenses pass. The `test` job **fails**: `buildNavSections.test.ts` ("includes the correct services in each built-in section" and "hides a service via deniedServices alone") still expects the Network section without `networks`.

</details>

<details>
<summary><strong>How it is implemented</strong></summary>

**List procedure** — Neutron filters are forwarded and the search runs in the BFF (`packages/aurora/src/server/Network/routers/networksRouter.ts:103`):

```ts
        // Build query params for Neutron API (forward applicable filters)
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        const { project_id, searchTerm, ...neutronParams } = input
        const params = appendQueryParamsFromObject(neutronParams, LIST_NETWORKS_QUERY_KEY_MAP)

        const response = await requestOrThrow(
          () => network.get(withQuery(NETWORKS_BASE_URL, params)),
          NetworkErrorHandlers.list
        )
```

The second argument should be `{ keyMap: … }`. The helper destructures it (`packages/aurora/src/server/helpers/queryParams.ts:31`):

```ts
  const { keyMap } = options ?? {}
```

There is one request with no `limit`/`marker` and no `networks_links` handling, so the result is whatever Neutron returns on its first page.

**Subnet enrichment** — a best-effort batched lookup (`packages/aurora/src/server/Network/routers/networksRouter.ts:48`):

```ts
const fetchSubnetDetails = async (network: NetworkService, subnetIds: string[]): Promise<SubnetDetail[]> => {
  if (subnetIds.length === 0) return []
  try {
    const params = appendQueryParamsFromObject({ id: subnetIds })
    const response = await network.get(withQuery(SUBNETS_BASE_URL, params))
    if (!response.ok) return []
    const data = await response.json()
    return parseOrThrow(SubnetListResponseSchema, data, "networksRouter.subnets").subnets
  } catch {
    return []
  }
}
```

Array values become repeated `id=` params. `getById` merges the result in as `subnet_details` (`networksRouter.ts:141-146`). Path IDs go through `validateAndEncodeResourceId` in `networkUrl()` (`networksRouter.ts:37`).

**Write procedures** — `create` builds the body with `pickDefined` and deliberately omits `project_id`, so Neutron takes ownership from the rescoped token. The create schema defaults `shared` and `router:external` to `false` (`packages/aurora/src/server/Network/types/network.ts:148`, `:150`), so both are always sent. `update` forwards `provider:*` when the caller supplies them. `delete` doesn't parse a body (Neutron returns 204).

**List UI** — the input and the query key are separate, so the list re-queries only when a search is submitted. The empty branch returns before the toolbar (`…/network/networks/-components/NetworksList.tsx:99`):

```tsx
  if (networks.length === 0) {
    return (
      <Stack direction="vertical" gap="4">
        <ContentHeader title={t`Networks`} projectId={projectId} />
        <Status
          status={hasSearch ? "no-matches" : "empty"}
          title={hasSearch ? t`No Matching Networks` : t`No Networks Found`}
          body={
            hasSearch
              ? t`No networks match your search. Clear the search to view all networks.`
              : t`There are no networks in this project. Networks can be created through the API or CLI.`
          }
        />
      </Stack>
    )
  }
```

Permission and create are placeholders (`NetworksList.tsx:53`):

```tsx
  // Check permissions (TODO: implement permission checking)
  const canCreate = true // Placeholder

  const handleCreateClick = () => {
    // TODO: Open create network modal
    console.log("Create network clicked")
  }
```

Rows navigate to the detail page on click. `ClipboardText` stops propagation itself, so copying an ID doesn't navigate.

**Detail route** — `beforeLoad` redirects to the list when the catalog has no `network`/`neutron` entry (`…/network/networks/$networkId/index.tsx:37`). The loader fetches the network for the tab title only (`$networkId/index.tsx:20`):

```tsx
  loader: async ({ context, params }) => {
    const network = await context.trpcClient?.network.networks.getById.query({
      project_id: params.projectId,
      network_id: params.networkId,
    })
    return { networkTitle: network?.name || network?.id || null }
  },
```

The component then fetches the same data again with `trpcReact.network.networks.getById.useQuery` (`:62`) and renders `NetworkDetailsView`.

**Wiring** — `networks: networksRouter` in `packages/aurora/src/server/Network/routers/index.ts:17`. The nav entry is gated by `isEnabled("networks")` inside the existing `serviceIndex["network"]` check (`packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts:60`). `routeTree.gen.ts` is regenerated with the three new routes.

**Git ignore** (`.gitignore:12`):

```
.claude/*
!.claude/skills/
!.claude/agents/
CLAUDE*
```

</details>

<details>
<summary><strong>What it affects (blast radius)</strong></summary>

- **New tRPC surface `network.networks.*`** — no consumers outside the PR's own routes. The key is new on `main`, so nothing existing breaks. Open PRs #1385 and #1383 define the same key with a different procedure set (CR10).
- **Service key `networks`** — used only by the new routes' `staticData` and the nav entry. The consumer docs list service keys in `packages/aurora/README.md:183` and `:210` and in `apps/dashboard/.env.example:11`. The PR adds `networks` to none of them (all three already lack `routers`). Host apps with an `enabledServices` allowlist won't see Networks until they add `networks`.
- **Side nav** — Networks now appears first in the Network section wherever a network-type service is in the catalog. This changes the section's service order, which is why two existing `buildNavSections.test.ts` assertions fail in CI.
- **Routers detail route** — behaviour is unchanged (same literal id), but the edit causes a content conflict with open PR #1377 (CR11).
- **No policy-file or permission-key changes.** `network:networks:*` keys already exist in the Network permission router and are still unused.
- **Repo tooling** — the `.gitignore` change affects every contributor's working tree: files under `.claude/skills/` and `.claude/agents/` become trackable (CR9).
- **Release** — a `minor` bump of `@cobaltcore-dev/aurora` via the changeset.

</details>

---

## QA Test Plan

<details>
<summary><strong>Core Path</strong></summary>

1. Open a project with Neutron in the catalog. Confirm "Networks" is the first item under Network in the side nav.
2. Open Networks. The list shows Name, ID (copyable, truncated), Status, Admin State, Shared, External, and an item count.
3. Type part of a network name and press Enter. The list narrows. Check that a description match also hits.
4. Clear the search with the input's clear button. The full list returns.
5. Click Refresh. The list re-fetches.
6. Click a row. The detail page opens with the network name as heading and tab title, plus a "Back to Networks" action.
7. Check Network Information (ID, name, description, status, admin state, shared, external, MTU, port security) against `openstack network show`.
8. Check the Subnets table (CIDR, IP version, gateway, allocation pools, DHCP) against `openstack subnet list --network <id>`.
9. As admin, open a provider network. The Provider Network section shows type, physical network and segmentation ID.
10. Click "Back to Networks". You return to the list.

</details>

<details>
<summary><strong>Edge Cases</strong></summary>

- Search for a string that matches nothing. The "No Matching Networks" state appears, and there is no search box to clear it (CR3, `NetworksList.tsx:99`).
- Project with no networks: "No Networks Found" appears, and there is no Create button (`NetworksList.tsx:99`).
- Click "Create Network". Nothing happens apart from a console log (CR4, `NetworksList.tsx:58`).
- Copy an ID from a list row. It must not navigate to the detail page.
- Network with subnets where `/v2.0/subnets` fails, e.g. a policy denies it or the response doesn't parse. The detail page says "No Subnets" (CR2, `networksRouter.ts:53`).
- Network with no subnets: the "No Subnets" empty state is correct here (`NetworkDetailsView.tsx:84`).
- Deployment with `pagination_max_limit` set below the network count: the list stops at the first page (CR6, `networksRouter.ts:108`).
- Open a detail URL with a non-existent network ID. The parent route's error component ("Back to Networks") shows, not the in-page "Network Not Found" (CR7, `networks.tsx:34`).
- User without network list permission: the list shows "You do not have permission to view networks." with a Retry button (`NetworksList.tsx:79`).
- Catalog with a `network` type but no `neutron`: the detail route redirects to the list (`$networkId/index.tsx:37`), and the list then shows its error state.
- Reload the list after a search, or press Back from a detail page. The search is lost (I1).
- Watch the network tab on a detail visit: `getById` (and the subnets lookup) runs twice (CR7).
- Host app with `enabledServices` that omits `networks`: the nav entry is hidden, but the routes are still reachable by URL.

</details>

---

_Analyzed 2026-10-16 · commit `e6b1e69` · read-only, CI from PR API · skill: document-pr_

<!-- related:auto — generated from pr/issue properties by tools/update-related.py; do not edit by hand -->
## Related

- plan · 2026-10-12 · [2026-10-12-networks-epic-1019-analysis](../../plans/2026-10-12-networks-epic-1019-analysis.md)
- plan · 2026-10-12 · [2026-10-12-networks-phase-1-read-operations](../../plans/2026-10-12-networks-phase-1-read-operations.md)
